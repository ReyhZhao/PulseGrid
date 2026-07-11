import logging
import signal

from django.core.management.base import BaseCommand

from apps.alerts.services import dispatch_event
from apps.audit.services import forward_event
from pulsegrid import queues

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Consume the notification and audit queues: deliver alerts "
        "(email/webhook) and forward audit events to the MSSP platform."
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Drain currently queued jobs and exit")

    def handle(self, *args, **options):
        self._running = True

        def stop(signum, frame):
            self._running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        self.stdout.write("PulseGrid dispatcher started (notifications + audit forwarding)")
        while self._running:
            try:
                job = queues.pop_dispatch_job(timeout_seconds=5)
            except Exception:
                logger.exception("failed to read dispatch queues")
                continue
            if job is None:
                if options["once"]:
                    break
                continue
            kind, payload = job
            try:
                if kind == "audit":
                    forward_event(payload["audit_event_id"])
                else:
                    dispatch_event(payload["event_id"])
            except Exception:
                logger.exception("failed to process %s job %r", kind, payload)
        self.stdout.write("PulseGrid dispatcher stopped")
