import logging
import signal

from django.core.management.base import BaseCommand

from apps.alerts.services import dispatch_event
from pulsegrid import queues

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume the notification queue and deliver alerts (email/webhook)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Drain currently queued jobs and exit")

    def handle(self, *args, **options):
        self._running = True

        def stop(signum, frame):
            self._running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        self.stdout.write("PulseGrid notification dispatcher started")
        while self._running:
            try:
                job = queues.pop_notification(timeout_seconds=5)
            except Exception:
                logger.exception("failed to read notification queue")
                continue
            if job is None:
                if options["once"]:
                    break
                continue
            try:
                dispatch_event(job["event_id"])
            except Exception:
                logger.exception("failed to dispatch event %r", job)
        self.stdout.write("PulseGrid notification dispatcher stopped")
