import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.monitors.scheduler import schedule_due_monitors

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Continuously enqueue due monitor checks onto the region work queues."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run a single tick and exit")

    def handle(self, *args, **options):
        tick = settings.PULSEGRID["SCHEDULER_TICK_SECONDS"]
        self._running = True

        def stop(signum, frame):
            self._running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        self.stdout.write(f"PulseGrid scheduler started (tick: {tick}s)")
        while self._running:
            started = time.monotonic()
            try:
                schedule_due_monitors()
            except Exception:
                logger.exception("scheduler tick failed")
            if options["once"]:
                break
            elapsed = time.monotonic() - started
            time.sleep(max(tick - elapsed, 0.5))
        self.stdout.write("PulseGrid scheduler stopped")
