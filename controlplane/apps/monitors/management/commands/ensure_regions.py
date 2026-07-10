from django.conf import settings
from django.core.management.base import BaseCommand

from apps.monitors.models import Region


class Command(BaseCommand):
    help = "Create the regions listed in PULSEGRID_REGIONS ('code:Name,code:Name') if missing."

    def handle(self, *args, **options):
        spec = settings.PULSEGRID["DEFAULT_REGIONS"]
        created = 0
        for entry in spec.split(","):
            entry = entry.strip()
            if not entry:
                continue
            code, _, name = entry.partition(":")
            _, was_created = Region.objects.get_or_create(
                code=code.strip(), defaults={"name": name.strip() or code.strip()}
            )
            created += int(was_created)
        self.stdout.write(f"Regions ensured ({created} created)")
