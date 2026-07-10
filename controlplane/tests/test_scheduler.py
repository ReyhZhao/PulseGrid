from datetime import timedelta

import pytest
from django.utils import timezone

from apps.monitors.models import Monitor
from apps.monitors.scheduler import schedule_due_monitors
from pulsegrid import queues

pytestmark = pytest.mark.django_db


def test_due_monitor_fans_out_to_all_regions(monitor, regions):
    enqueued = schedule_due_monitors()
    assert enqueued == 2  # empty regions list = every active region

    for region in regions:
        tasks = queues.pop_check_tasks(region.code, 10)
        assert len(tasks) == 1
        task = tasks[0]
        assert task["monitor_id"] == str(monitor.id)
        assert task["region"] == region.code
        assert task["url"] == monitor.url
        assert task["timeout"] == monitor.timeout_seconds


def test_monitor_with_explicit_regions_only_targets_those(org, regions):
    Monitor.objects.create(
        organization=org, name="EU only", url="https://example.com", regions=["eu-west"]
    )
    assert schedule_due_monitors() == 1
    assert len(queues.pop_check_tasks("eu-west", 10)) == 1
    assert queues.pop_check_tasks("us-east", 10) == []


def test_next_check_at_advances_without_drift(monitor, regions):
    start = monitor.next_check_at
    schedule_due_monitors()
    monitor.refresh_from_db()
    assert monitor.next_check_at > timezone.now()
    # anchored to the original deadline, not the tick time
    assert (monitor.next_check_at - start).total_seconds() % monitor.interval_seconds == 0


def test_not_due_and_paused_monitors_are_skipped(monitor, regions):
    monitor.next_check_at = timezone.now() + timedelta(seconds=30)
    monitor.save()
    assert schedule_due_monitors() == 0

    monitor.next_check_at = timezone.now() - timedelta(seconds=30)
    monitor.is_paused = True
    monitor.save()
    assert schedule_due_monitors() == 0


def test_second_tick_enqueues_nothing_until_interval_elapses(monitor, regions):
    assert schedule_due_monitors() > 0
    assert schedule_due_monitors() == 0


def test_tcp_task_payload(org, regions):
    Monitor.objects.create(
        organization=org,
        name="DB",
        monitor_type=Monitor.Type.TCP,
        host="db.example.com",
        port=5432,
        regions=["eu-west"],
    )
    schedule_due_monitors()
    task = queues.pop_check_tasks("eu-west", 1)[0]
    assert task["type"] == "tcp"
    assert task["host"] == "db.example.com"
    assert task["port"] == 5432
