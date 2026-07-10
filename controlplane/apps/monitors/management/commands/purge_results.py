from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.monitors.models import CheckResult


class Command(BaseCommand):
    help = "Delete check results older than the retention window (run from a CronJob)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)
        parser.add_argument("--batch-size", type=int, default=10000)

    def handle(self, *args, **options):
        days = options["days"] or settings.PULSEGRID["RESULT_RETENTION_DAYS"]
        cutoff = timezone.now() - timezone.timedelta(days=days)
        total = 0
        while True:
            ids = list(
                CheckResult.objects.filter(checked_at__lt=cutoff).values_list("id", flat=True)[
                    : options["batch_size"]
                ]
            )
            if not ids:
                break
            deleted, _ = CheckResult.objects.filter(id__in=ids).delete()
            total += deleted
        self.stdout.write(f"Purged {total} result(s) older than {days} day(s)")
