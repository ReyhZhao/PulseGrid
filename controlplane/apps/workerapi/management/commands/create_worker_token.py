from django.core.management.base import BaseCommand, CommandError

from apps.monitors.models import Region
from apps.workerapi.models import Worker


class Command(BaseCommand):
    help = "Issue a token for a monitoring worker. The token is printed once; store it safely."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Worker name, e.g. 'eu-west-1a'")
        parser.add_argument("--region", required=True, help="Region code the worker serves")

    def handle(self, *args, **options):
        try:
            region = Region.objects.get(code=options["region"])
        except Region.DoesNotExist as exc:
            codes = ", ".join(Region.objects.values_list("code", flat=True)) or "(none)"
            raise CommandError(
                f"Unknown region '{options['region']}'. Known regions: {codes}. "
                "Run 'manage.py ensure_regions' or create one in the admin."
            ) from exc
        worker, token = Worker.issue(options["name"], region)

        from apps.audit.models import Severity
        from apps.audit.services import record as audit

        audit(
            "worker.token_created",
            f"Worker token issued for '{worker.name}' in region '{region.code}'",
            severity=Severity.HIGH,
            actor="cli",
            actor_type="system",
            worker_id=worker.id,
            region=region.code,
        )

        self.stdout.write(f"Worker '{worker.name}' created for region '{region.code}'.")
        self.stdout.write(f"WORKER_TOKEN={token}")
