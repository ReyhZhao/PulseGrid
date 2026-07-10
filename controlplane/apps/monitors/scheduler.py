"""
Monitor scheduler.

Runs as its own process (`manage.py runscheduler`). Each tick it grabs a
batch of due monitors with SELECT ... FOR UPDATE SKIP LOCKED, fans out one
check task per region onto the Redis queues, and advances `next_check_at`.
SKIP LOCKED makes it safe to run several scheduler replicas for HA.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from pulsegrid import queues

from .models import Monitor

logger = logging.getLogger(__name__)


def schedule_due_monitors(now=None) -> int:
    """Enqueue checks for every due monitor. Returns tasks enqueued."""
    now = now or timezone.now()
    batch_size = settings.PULSEGRID["SCHEDULER_BATCH_SIZE"]
    tasks_by_region: dict[str, list[dict]] = defaultdict(list)

    with transaction.atomic():
        due = Monitor.objects.filter(is_paused=False, next_check_at__lte=now)
        # Lets several scheduler replicas run concurrently on PostgreSQL;
        # SQLite (tests/dev) has no row locking, so skip it there.
        if connection.features.has_select_for_update_skip_locked:
            due = due.select_for_update(skip_locked=True)
        due = due.order_by("next_check_at")[:batch_size]
        for monitor in due:
            for region_code in monitor.effective_regions():
                tasks_by_region[region_code].append(monitor.to_check_task(region_code, now))
            # Anchor to the previous deadline (not `now`) so intervals do not
            # drift when the scheduler tick lands late.
            next_at = monitor.next_check_at
            while next_at <= now:
                next_at += timedelta(seconds=monitor.interval_seconds)
            monitor.next_check_at = next_at
            monitor.save(update_fields=["next_check_at"])

    total = 0
    for region_code, tasks in tasks_by_region.items():
        total += queues.push_check_tasks(region_code, tasks)
    if total:
        logger.info("scheduled %d check task(s) across %d region(s)", total, len(tasks_by_region))
    return total
