# Existing users predate the onboarding wizard — mark them as already
# onboarded so they are not funneled into /welcome on their next login.

from django.db import migrations
from django.utils import timezone


def backfill_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("accounts", "UserProfile")
    now = timezone.now()
    for user in User.objects.filter(profile__isnull=True):
        UserProfile.objects.create(user=user, onboarded_at=now)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_organizationinvitation_userprofile"),
    ]

    operations = [
        migrations.RunPython(backfill_profiles, noop),
    ]
