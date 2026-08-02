"""Read-only, organization-scoped `pgr_` API tokens.

This is a second authentication path into a multi-tenant control plane, so the
cross-tenant and read-only assertions here are the substance of the feature.
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.alerts.models import AlertEvent, NotificationChannel
from apps.apitokens.models import ApiToken
from apps.audit.models import AuditEvent, Severity
from apps.monitors.models import CheckResult, Monitor

pytestmark = pytest.mark.django_db


# --- issuing ------------------------------------------------------------


def test_token_is_stored_hashed_and_plaintext_returned_once(org):
    token, plaintext = ApiToken.issue("polaris", org)

    assert plaintext.startswith("pgr_")
    assert token.token_hash == ApiToken.hash_token(plaintext)
    # The plaintext must not be recoverable from the row.
    assert plaintext not in str(token.__dict__.values())
    assert ApiToken.objects.get(pk=token.pk).token_hash != plaintext


def test_token_holds_no_membership(org, api_token_and_key):
    """A machine principal is not a Django user: no member row appears."""
    assert org.memberships.count() == 1  # just the owning user


def test_create_api_token_command_prints_the_token_once(org):
    out = StringIO()
    call_command("create_api_token", "--name", "polaris", "--organization", org.slug, stdout=out)

    printed = out.getvalue()
    plaintext = printed.split("PULSEGRID_API_TOKEN=")[1].strip()
    assert plaintext.startswith("pgr_")
    assert ApiToken.objects.get(name="polaris").token_hash == ApiToken.hash_token(plaintext)
    assert AuditEvent.objects.filter(event_type="api_token.created", severity=Severity.HIGH).exists()


def test_create_api_token_command_accepts_a_uuid(org):
    out = StringIO()
    call_command("create_api_token", "--name", "by-uuid", "--organization", str(org.id), stdout=out)
    assert ApiToken.objects.filter(name="by-uuid", organization=org).exists()


def test_create_api_token_command_rejects_an_unknown_organization(db):
    with pytest.raises(CommandError):
        call_command("create_api_token", "--name", "nope", "--organization", "no-such-org")


def test_admin_cannot_add_a_token(superuser, client, api_token_and_key):
    """The admin form can't return a plaintext, so adding there would only save
    a row with an empty hash. Issuing is the management command's job; the
    admin page exists to revoke and to show last use."""
    client.force_login(superuser)

    assert client.get("/admin/apitokens/apitoken/add/").status_code == 403
    # Revoking, the reason the page exists, still works.
    token, _ = api_token_and_key
    assert client.get(f"/admin/apitokens/apitoken/{token.pk}/change/").status_code == 200


# --- authentication -----------------------------------------------------


def test_token_reads_monitors_of_its_own_organization(token_api, monitor):
    response = token_api.get("/api/v1/monitors/")
    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [str(monitor.id)]


def test_token_reads_alert_events_and_results(token_api, monitor):
    AlertEvent.objects.create(monitor=monitor, event_type=AlertEvent.Type.DOWN, summary="down")
    CheckResult.objects.create(
        monitor=monitor, region_code="eu-west", checked_at=timezone.now(), ok=True, latency_ms=10
    )

    assert token_api.get("/api/v1/alerts/").data["count"] == 1
    assert len(token_api.get(f"/api/v1/monitors/{monitor.id}/results/").data) == 1


def test_token_updates_last_used_at(token_api, api_token_and_key, monitor):
    token, _ = api_token_and_key
    assert token.last_used_at is None

    token_api.get("/api/v1/monitors/")

    token.refresh_from_db()
    assert token.last_used_at is not None


def test_invalid_token_is_rejected_and_audited(db):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer pgr_not-a-real-token")

    # 403 rather than 401: SessionAuthentication is first in
    # DEFAULT_AUTHENTICATION_CLASSES and suppresses the WWW-Authenticate
    # challenge, which is what keeps anonymous SPA requests answering 403.
    assert client.get("/api/v1/monitors/").status_code == 403
    assert AuditEvent.objects.filter(
        event_type="api_token.auth_failed", severity=Severity.HIGH
    ).exists()


def test_inactive_token_is_rejected_and_audited(api_token_and_key):
    token, plaintext = api_token_and_key
    token.is_active = False
    token.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")

    assert client.get("/api/v1/monitors/").status_code == 403
    assert AuditEvent.objects.filter(
        event_type="api_token.auth_failed", severity=Severity.HIGH
    ).exists()


# --- read-only ----------------------------------------------------------


def test_token_cannot_write_monitors(token_api, monitor, org):
    payload = {"organization": str(org.id), "name": "new", "url": "https://example.org/"}
    assert token_api.post("/api/v1/monitors/", payload, format="json").status_code == 403
    assert token_api.patch(
        f"/api/v1/monitors/{monitor.id}/", {"name": "renamed"}, format="json"
    ).status_code == 403
    assert token_api.delete(f"/api/v1/monitors/{monitor.id}/").status_code == 403
    assert token_api.post(f"/api/v1/monitors/{monitor.id}/pause/").status_code == 403

    monitor.refresh_from_db()
    assert monitor.name == "Example"
    assert not monitor.is_paused
    assert Monitor.objects.count() == 1


def test_token_cannot_write_channels(token_api, org):
    payload = {
        "organization": str(org.id),
        "name": "ops",
        "channel_type": "email",
        "config": {"to": ["ops@example.com"]},
    }
    assert token_api.post("/api/v1/channels/", payload, format="json").status_code == 403
    assert NotificationChannel.objects.count() == 0


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/me",
        "/api/v1/orgs/",
        "/api/v1/audit/",
        "/api/v1/push/subscriptions",
        "/api/v1/admin/orgs/",
    ],
)
def test_token_has_no_access_to_user_scoped_endpoints(token_api, org, path):
    """Only IsOrganizationMember admits a token principal; everything else
    still demands a logged-in user."""
    assert token_api.get(path).status_code == 403


# --- tenancy ------------------------------------------------------------


def test_token_cannot_read_another_organizations_monitors(other_token_api, monitor):
    response = other_token_api.get("/api/v1/monitors/")
    assert response.status_code == 200
    assert response.data["results"] == []

    assert other_token_api.get(f"/api/v1/monitors/{monitor.id}/").status_code == 404
    assert other_token_api.get(f"/api/v1/monitors/{monitor.id}/stats/").status_code == 404
    assert other_token_api.get(f"/api/v1/monitors/{monitor.id}/results/").status_code == 404


def test_token_cannot_read_another_organizations_alerts(other_token_api, monitor):
    AlertEvent.objects.create(monitor=monitor, event_type=AlertEvent.Type.DOWN, summary="down")
    assert other_token_api.get("/api/v1/alerts/").data["count"] == 0


def test_organization_query_param_cannot_widen_a_tokens_scope(other_token_api, monitor, org):
    response = other_token_api.get(f"/api/v1/monitors/?organization={org.id}")
    assert response.data["results"] == []
