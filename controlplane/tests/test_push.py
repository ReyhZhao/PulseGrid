"""Web push (VAPID) notifications: subscriptions, delivery, statistics."""

import json
from unittest import mock

import pytest
from rest_framework.test import APIClient

from apps.alerts import push, services
from apps.alerts.models import (
    AlertEvent,
    NotificationChannel,
    NotificationLog,
    PushDelivery,
    PushSubscription,
)


@pytest.mark.django_db
class TestVapidPublicKey:
    def test_returns_configured_public_key(self, api, settings):
        settings.VAPID_PUBLIC_KEY = "test-public-key"
        response = api.get("/api/v1/push/vapid-public-key")
        assert response.status_code == 200
        assert response.json() == {"public_key": "test-public-key"}

    def test_requires_authentication(self, db):
        response = APIClient().get("/api/v1/push/vapid-public-key")
        assert response.status_code == 403


SUBSCRIPTION = {
    "endpoint": "https://push.example.com/send/abc123",
    "p256dh": "BPubKey",
    "auth": "authsecret",
}


@pytest.mark.django_db
class TestPushSubscriptions:
    def test_register_creates_subscription_for_current_user(self, api, user):
        response = api.post("/api/v1/push/subscriptions", SUBSCRIPTION, format="json")
        assert response.status_code == 201
        subscription = user.push_subscriptions.get()
        assert subscription.endpoint == SUBSCRIPTION["endpoint"]
        assert subscription.p256dh == SUBSCRIPTION["p256dh"]
        assert subscription.auth == SUBSCRIPTION["auth"]

    def test_reregistering_same_endpoint_is_idempotent(self, api, user):
        api.post("/api/v1/push/subscriptions", SUBSCRIPTION, format="json")
        response = api.post(
            "/api/v1/push/subscriptions", {**SUBSCRIPTION, "auth": "rotated"}, format="json"
        )
        assert response.status_code == 200
        subscription = user.push_subscriptions.get()
        assert subscription.auth == "rotated"

    def test_cannot_hijack_another_users_endpoint(self, api, other_api, user, other_user):
        # other_user owns the endpoint; alice must not be able to rebind it to
        # herself or overwrite its keys.
        assert other_api.post("/api/v1/push/subscriptions", SUBSCRIPTION, format="json").status_code == 201
        response = api.post(
            "/api/v1/push/subscriptions", {**SUBSCRIPTION, "auth": "attacker"}, format="json"
        )
        assert response.status_code == 409
        subscription = other_user.push_subscriptions.get()
        assert subscription.auth == SUBSCRIPTION["auth"]  # untouched
        assert not user.push_subscriptions.exists()

    def test_register_requires_endpoint(self, api):
        response = api.post(
            "/api/v1/push/subscriptions", {"p256dh": "k", "auth": "a"}, format="json"
        )
        assert response.status_code == 400

    def test_unsubscribe_deletes_own_subscription(self, api, user):
        api.post("/api/v1/push/subscriptions", SUBSCRIPTION, format="json")
        response = api.delete(
            "/api/v1/push/subscriptions",
            {"endpoint": SUBSCRIPTION["endpoint"]},
            format="json",
        )
        assert response.status_code == 204
        assert not user.push_subscriptions.exists()

    def test_cannot_delete_another_users_subscription(self, api, other_api, other_user):
        other_api.post("/api/v1/push/subscriptions", SUBSCRIPTION, format="json")
        response = api.delete(
            "/api/v1/push/subscriptions",
            {"endpoint": SUBSCRIPTION["endpoint"]},
            format="json",
        )
        assert response.status_code == 204
        assert other_user.push_subscriptions.exists()


@pytest.mark.django_db
class TestGenerateVapidKeys:
    def test_prints_a_usable_key_pair(self, capsys):
        from django.core.management import call_command

        call_command("generate_vapid_keys")
        output = capsys.readouterr().out
        assert "VAPID_PUBLIC_KEY=" in output
        assert "VAPID_PRIVATE_KEY=" in output


@pytest.mark.django_db
class TestPushChannel:
    def _create(self, api, org, user_ids, name="On-call push"):
        return api.post(
            "/api/v1/channels/",
            {
                "organization": str(org.id),
                "name": name,
                "channel_type": "push",
                "config": {"user_ids": user_ids},
            },
            format="json",
        )

    def test_create_with_org_members(self, api, org, user):
        response = self._create(api, org, [user.id])
        assert response.status_code == 201
        assert response.json()["channel_type"] == "push"
        assert response.json()["config"]["user_ids"] == [user.id]

    def test_rejects_users_outside_the_organization(self, api, org, other_user):
        response = self._create(api, org, [other_user.id])
        assert response.status_code == 400
        assert "config" in response.json()

    def test_rejects_empty_recipient_list(self, api, org):
        response = self._create(api, org, [])
        assert response.status_code == 400


@pytest.fixture
def vapid(settings):
    settings.VAPID_PUBLIC_KEY = "server-public-key"
    settings.VAPID_PRIVATE_KEY = "server-private-key"
    settings.VAPID_SUBJECT = "mailto:ops@pulsegrid.test"


@pytest.fixture
def sent_pushes(monkeypatch):
    """Capture pywebpush calls made by the delivery code."""
    calls = []

    def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
        calls.append(
            {
                "subscription_info": subscription_info,
                "data": json.loads(data),
                "vapid_private_key": vapid_private_key,
                "vapid_claims": vapid_claims,
            }
        )

    monkeypatch.setattr(push, "webpush", fake_webpush)
    return calls


def make_subscription(user, endpoint="https://push.example.com/send/abc123"):
    return PushSubscription.objects.create(
        user=user, endpoint=endpoint, p256dh="BPubKey", auth="authsecret"
    )


def make_push_channel(org, users):
    return NotificationChannel.objects.create(
        organization=org,
        name="On-call push",
        channel_type=NotificationChannel.Type.PUSH,
        config={"user_ids": [u.id for u in users]},
    )


def make_down_event(monitor):
    return AlertEvent.objects.create(
        monitor=monitor,
        event_type=AlertEvent.Type.DOWN,
        summary=f"{monitor.name} is DOWN",
        details={"error": "connection timed out", "regions_down": 2, "status_code": None},
    )


@pytest.mark.django_db
class TestPushDelivery:
    def test_sends_rich_payload_to_every_subscription(
        self, vapid, sent_pushes, org, user, monitor
    ):
        make_subscription(user, "https://push.example.com/send/phone")
        make_subscription(user, "https://push.example.com/send/laptop")
        channel = make_push_channel(org, [user])
        event = make_down_event(monitor)

        delivered = services.dispatch_event(event.id)

        assert delivered == 1
        endpoints = {c["subscription_info"]["endpoint"] for c in sent_pushes}
        assert endpoints == {
            "https://push.example.com/send/phone",
            "https://push.example.com/send/laptop",
        }
        payload = sent_pushes[0]["data"]
        assert payload["title"] == "🔴 PulseGrid alert: Example is DOWN"
        assert "connection timed out" in payload["body"]
        assert payload["alert"]["summary"] == "Example is DOWN"
        assert payload["alert"]["status"] == "open"
        assert payload["alert"]["event_type"] == "down"
        assert payload["alert"]["error"] == "connection timed out"
        assert payload["monitor"]["name"] == "Example"
        assert payload["monitor"]["target"] == monitor.target
        assert payload["url"] == "/alerts"
        assert sent_pushes[0]["vapid_private_key"] == "server-private-key"
        assert sent_pushes[0]["vapid_claims"] == {"sub": "mailto:ops@pulsegrid.test"}
        log = NotificationLog.objects.get(channel=channel)
        assert log.status == NotificationLog.Status.SENT

    def test_resolved_event_payload_carries_resolution(
        self, vapid, sent_pushes, org, user, monitor
    ):
        make_subscription(user)
        make_push_channel(org, [user])
        event = make_down_event(monitor)
        services.resolve_event(monitor, AlertEvent.Type.DOWN, "Example recovered in all regions")

        services.dispatch_event(event.id)

        payload = sent_pushes[0]["data"]
        assert payload["title"] == "✅ PulseGrid resolved: Example is DOWN"
        assert payload["alert"]["status"] == "resolved"
        assert payload["alert"]["kind"] == "resolved"
        assert "Example recovered in all regions" in payload["body"]

    def test_fails_loudly_when_vapid_keys_missing(self, settings, sent_pushes, org, user, monitor):
        settings.VAPID_PRIVATE_KEY = ""
        make_subscription(user)
        channel = make_push_channel(org, [user])
        event = make_down_event(monitor)

        assert services.dispatch_event(event.id) == 0
        log = NotificationLog.objects.get(channel=channel)
        assert log.status == NotificationLog.Status.FAILED

    def test_stale_subscriptions_are_pruned(self, vapid, monkeypatch, org, user, monitor):
        gone = make_subscription(user, "https://push.example.com/send/gone")
        alive = make_subscription(user, "https://push.example.com/send/alive")
        make_push_channel(org, [user])
        event = make_down_event(monitor)

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            if subscription_info["endpoint"].endswith("/gone"):
                response = mock.Mock(status_code=410)
                raise push.WebPushException("gone", response=response)

        monkeypatch.setattr(push, "webpush", fake_webpush)
        assert services.dispatch_event(event.id) == 1
        assert not PushSubscription.objects.filter(pk=gone.pk).exists()
        assert PushSubscription.objects.filter(pk=alive.pk).exists()

    def test_recipients_no_longer_in_the_org_are_skipped(
        self, vapid, sent_pushes, org, user, other_user, monitor
    ):
        # other_user was configured on the channel but has since left the org.
        make_subscription(user, "https://push.example.com/send/member")
        make_subscription(other_user, "https://push.example.com/send/outsider")
        channel = make_push_channel(org, [user])
        channel.config["user_ids"].append(other_user.id)
        channel.save(update_fields=["config"])
        event = make_down_event(monitor)

        services.dispatch_event(event.id)

        endpoints = {c["subscription_info"]["endpoint"] for c in sent_pushes}
        assert endpoints == {"https://push.example.com/send/member"}


@pytest.mark.django_db
class TestSendTestPush:
    def test_sends_a_test_notification_to_own_devices(self, vapid, sent_pushes, api, user):
        make_subscription(user)
        response = api.post("/api/v1/push/test")
        assert response.status_code == 200
        assert len(sent_pushes) == 1
        payload = sent_pushes[0]["data"]
        assert "test" in payload["title"].lower()
        assert payload["url"] == "/profile"

    def test_400_when_user_has_no_subscription(self, vapid, sent_pushes, api):
        response = api.post("/api/v1/push/test")
        assert response.status_code == 400

    def test_400_when_push_is_not_configured(self, settings, api, user):
        settings.VAPID_PRIVATE_KEY = ""
        make_subscription(user)
        response = api.post("/api/v1/push/test")
        assert response.status_code == 400


@pytest.mark.django_db
class TestPushStats:
    def test_dispatch_records_one_delivery_per_recipient(
        self, vapid, sent_pushes, org, user, monitor
    ):
        make_subscription(user, "https://push.example.com/send/phone")
        make_subscription(user, "https://push.example.com/send/laptop")
        make_push_channel(org, [user])
        event = make_down_event(monitor)

        services.dispatch_event(event.id)

        delivery = PushDelivery.objects.get(user=user)
        assert delivery.event_id == event.id
        assert delivery.kind == "opened"

    def test_daily_counts_over_lookback_window(self, vapid, sent_pushes, api, org, user, other_user, monitor):
        from datetime import timedelta

        from django.utils import timezone

        make_subscription(user)
        make_push_channel(org, [user])
        services.dispatch_event(make_down_event(monitor).id)
        services.dispatch_event(make_down_event(monitor).id)
        two_days_ago = make_down_event(monitor)
        services.dispatch_event(two_days_ago.id)
        PushDelivery.objects.filter(event=two_days_ago).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        # Outside the window and other users never show up.
        ancient = make_down_event(monitor)
        services.dispatch_event(ancient.id)
        PushDelivery.objects.filter(event=ancient).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        PushDelivery.objects.create(user=other_user, event=two_days_ago, kind="opened")

        response = api.get("/api/v1/push/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert len(data["by_day"]) == 30
        assert data["total"] == 3
        today = timezone.now().date().isoformat()
        counts = {entry["date"]: entry["count"] for entry in data["by_day"]}
        assert counts[today] == 2
        assert sum(counts.values()) == 3

    def test_days_parameter_is_clamped(self, api):
        assert len(api.get("/api/v1/push/stats?days=7").json()["by_day"]) == 7
        assert len(api.get("/api/v1/push/stats?days=9999").json()["by_day"]) == 90
        assert len(api.get("/api/v1/push/stats?days=banana").json()["by_day"]) == 30
