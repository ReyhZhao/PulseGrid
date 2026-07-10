import pytest
import responses as responses_lib
from django.core import mail

from apps.alerts.models import AlertEvent, NotificationChannel, NotificationLog
from apps.alerts.services import dispatch_event, open_event

pytestmark = pytest.mark.django_db


@pytest.fixture
def down_event(monitor):
    return open_event(monitor, AlertEvent.Type.DOWN, summary=f"{monitor.name} is DOWN")


def test_email_notification_is_sent(org, monitor, down_event):
    NotificationChannel.objects.create(
        organization=org,
        name="Ops",
        channel_type=NotificationChannel.Type.EMAIL,
        config={"to": ["ops@example.com"]},
    )

    assert dispatch_event(down_event.id) == 1
    assert len(mail.outbox) == 1
    assert "ALERT" in mail.outbox[0].subject
    assert mail.outbox[0].to == ["ops@example.com"]
    log = NotificationLog.objects.get()
    assert log.status == NotificationLog.Status.SENT


@responses_lib.activate
def test_webhook_notification_posts_payload(org, monitor, down_event):
    responses_lib.add(responses_lib.POST, "https://hooks.example.com/pg", status=200)
    NotificationChannel.objects.create(
        organization=org,
        name="Hook",
        channel_type=NotificationChannel.Type.WEBHOOK,
        config={"url": "https://hooks.example.com/pg"},
    )

    assert dispatch_event(down_event.id) == 1
    body = responses_lib.calls[0].request.body
    assert b'"event_type": "down"' in body or b'"event_type":"down"' in body


@responses_lib.activate
def test_failed_webhook_is_logged_not_raised(org, monitor, down_event):
    responses_lib.add(responses_lib.POST, "https://hooks.example.com/pg", status=500)
    NotificationChannel.objects.create(
        organization=org,
        name="Hook",
        channel_type=NotificationChannel.Type.WEBHOOK,
        config={"url": "https://hooks.example.com/pg"},
    )

    assert dispatch_event(down_event.id) == 0
    log = NotificationLog.objects.get()
    assert log.status == NotificationLog.Status.FAILED


def test_channels_of_other_orgs_are_not_notified(other_org, monitor, down_event):
    NotificationChannel.objects.create(
        organization=other_org,
        name="Foreign",
        channel_type=NotificationChannel.Type.EMAIL,
        config={"to": ["foreign@example.com"]},
    )
    assert dispatch_event(down_event.id) == 0
    assert len(mail.outbox) == 0


def test_dispatch_unknown_event_is_noop(db, fake_redis):
    assert dispatch_event(999999) == 0
