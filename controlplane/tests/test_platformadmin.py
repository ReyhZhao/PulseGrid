"""Platform admin API: staff-only access, worker/region/org/user management,
platform stats and the global audit trail."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Membership, Organization
from apps.alerts.models import AlertEvent
from apps.audit.models import AuditEvent
from apps.monitors.models import CheckResult, Monitor, Region
from apps.monitors.scheduler import schedule_due_monitors
from apps.workerapi.models import Worker

pytestmark = pytest.mark.django_db


# --- access control ------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/workers/",
        "/api/v1/admin/regions/",
        "/api/v1/admin/orgs/",
        "/api/v1/admin/users/",
        "/api/v1/admin/audit/",
        "/api/v1/admin/stats",
    ],
)
def test_regular_user_gets_403(api, path):
    assert api.get(path).status_code == 403


def test_anonymous_gets_401_or_403(client):
    assert client.get("/api/v1/admin/stats").status_code in (401, 403)


def test_staff_and_superuser_have_access(staff_api, super_api):
    assert staff_api.get("/api/v1/admin/stats").status_code == 200
    assert super_api.get("/api/v1/admin/stats").status_code == 200


# --- workers ---------------------------------------------------------------


def test_create_worker_returns_token_once(staff_api, regions):
    response = staff_api.post(
        "/api/v1/admin/workers/", {"name": "probe-1", "region": "eu-west"}, format="json"
    )
    assert response.status_code == 201, response.data
    assert response.data["token"].startswith("pgw_")
    assert response.data["region"] == "eu-west"

    worker = Worker.objects.get(name="probe-1")
    assert worker.token_hash == Worker.hash_token(response.data["token"])
    assert AuditEvent.objects.filter(event_type="admin.worker_created").exists()

    # the token never appears in subsequent reads
    listing = staff_api.get("/api/v1/admin/workers/")
    assert "token" not in listing.data["results"][0]


def test_create_worker_unknown_region(staff_api, regions):
    response = staff_api.post(
        "/api/v1/admin/workers/", {"name": "probe-x", "region": "mars"}, format="json"
    )
    assert response.status_code == 400


def test_create_inactive_worker(staff_api, regions):
    response = staff_api.post(
        "/api/v1/admin/workers/",
        {"name": "probe-2", "region": "eu-west", "is_active": False},
        format="json",
    )
    assert response.status_code == 201
    assert Worker.objects.get(name="probe-2").is_active is False


def test_update_worker(staff_api, worker_and_token, regions):
    worker, _ = worker_and_token
    response = staff_api.patch(
        f"/api/v1/admin/workers/{worker.id}/",
        {"is_active": False, "region": "us-east"},
        format="json",
    )
    assert response.status_code == 200
    worker.refresh_from_db()
    assert worker.is_active is False
    assert worker.region.code == "us-east"
    assert AuditEvent.objects.filter(event_type="admin.worker_updated").exists()


def test_deactivated_worker_token_rejected(staff_api, worker_and_token):
    worker, token = worker_and_token
    staff_api.patch(f"/api/v1/admin/workers/{worker.id}/", {"is_active": False}, format="json")

    from rest_framework.test import APIClient

    worker_client = APIClient()
    worker_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert worker_client.post("/api/v1/worker/heartbeat", {}, format="json").status_code == 401


def test_rotate_worker_token(staff_api, worker_and_token):
    worker, old_token = worker_and_token
    response = staff_api.post(f"/api/v1/admin/workers/{worker.id}/rotate-token/")
    assert response.status_code == 200
    new_token = response.data["token"]
    assert new_token != old_token

    worker.refresh_from_db()
    assert worker.token_hash == Worker.hash_token(new_token)
    assert AuditEvent.objects.filter(event_type="admin.worker_token_rotated", severity="high").exists()


def test_delete_worker(staff_api, worker_and_token):
    worker, _ = worker_and_token
    assert staff_api.delete(f"/api/v1/admin/workers/{worker.id}/").status_code == 204
    assert not Worker.objects.filter(pk=worker.id).exists()
    assert AuditEvent.objects.filter(event_type="admin.worker_deleted", severity="high").exists()


# --- regions -----------------------------------------------------------------


def test_region_crud(staff_api):
    created = staff_api.post(
        "/api/v1/admin/regions/", {"code": "ap-south", "name": "Asia Pacific South"}, format="json"
    )
    assert created.status_code == 201, created.data

    region_id = created.data["id"]
    updated = staff_api.patch(
        f"/api/v1/admin/regions/{region_id}/", {"name": "AP South", "is_active": False}, format="json"
    )
    assert updated.status_code == 200
    region = Region.objects.get(pk=region_id)
    assert region.name == "AP South"
    assert region.is_active is False

    assert staff_api.delete(f"/api/v1/admin/regions/{region_id}/").status_code == 204
    assert not Region.objects.filter(pk=region_id).exists()
    for event in ("admin.region_created", "admin.region_updated", "admin.region_deleted"):
        assert AuditEvent.objects.filter(event_type=event).exists()


def test_region_code_is_immutable(staff_api, regions):
    response = staff_api.patch(
        f"/api/v1/admin/regions/{regions[0].id}/", {"code": "eu-central"}, format="json"
    )
    assert response.status_code == 400
    regions[0].refresh_from_db()
    assert regions[0].code == "eu-west"


def test_region_duplicate_code_rejected(staff_api, regions):
    response = staff_api.post(
        "/api/v1/admin/regions/", {"code": "eu-west", "name": "Duplicate"}, format="json"
    )
    assert response.status_code == 400


def test_region_with_workers_cannot_be_deleted(staff_api, worker_and_token, regions):
    region = regions[0]
    response = staff_api.delete(f"/api/v1/admin/regions/{region.id}/")
    assert response.status_code == 400
    assert Region.objects.filter(pk=region.id).exists()


def test_region_list_includes_worker_count(staff_api, worker_and_token, regions):
    response = staff_api.get("/api/v1/admin/regions/")
    counts = {r["code"]: r["worker_count"] for r in response.data}
    assert counts == {"eu-west": 1, "us-east": 0}


def test_inactive_region_hidden_from_user_facing_list(staff_api, api, regions):
    staff_api.patch(f"/api/v1/admin/regions/{regions[0].id}/", {"is_active": False}, format="json")
    response = api.get("/api/v1/regions/")
    assert [r["code"] for r in response.data] == ["us-east"]


# --- organizations -------------------------------------------------------


def test_org_list_includes_counts(staff_api, org, monitor):
    response = staff_api.get("/api/v1/admin/orgs/")
    row = next(o for o in response.data["results"] if o["id"] == str(org.id))
    assert row["member_count"] == 1
    assert row["monitor_count"] == 1
    assert row["is_active"] is True


def test_org_search(staff_api, org, other_org):
    response = staff_api.get("/api/v1/admin/orgs/?q=alice")
    names = [o["name"] for o in response.data["results"]]
    assert names == ["alice"]


def test_admin_creates_org(staff_api):
    response = staff_api.post("/api/v1/admin/orgs/", {"name": "Acme Corp"}, format="json")
    assert response.status_code == 201
    org = Organization.objects.get(name="Acme Corp")
    assert org.slug == "acme-corp"
    assert AuditEvent.objects.filter(event_type="admin.org_created").exists()


def test_admin_creates_org_with_owner(staff_api, user):
    response = staff_api.post(
        "/api/v1/admin/orgs/", {"name": "Acme Corp", "owner_username": "alice"}, format="json"
    )
    assert response.status_code == 201, response.data
    org = Organization.objects.get(name="Acme Corp")
    assert Membership.objects.filter(organization=org, user=user, role="owner").exists()


def test_admin_creates_org_unknown_owner_rejected(staff_api):
    response = staff_api.post(
        "/api/v1/admin/orgs/", {"name": "Acme", "owner_username": "nobody"}, format="json"
    )
    assert response.status_code == 400
    assert not Organization.objects.filter(name="Acme").exists()


def test_org_slug_collision_gets_suffix(staff_api, org):
    # "alice" already exists (personal org of the `user` fixture)
    response = staff_api.post("/api/v1/admin/orgs/", {"name": "Alice"}, format="json")
    assert response.status_code == 201
    assert response.data["slug"] == "alice-2"


def test_admin_renames_org(staff_api, org):
    response = staff_api.patch(f"/api/v1/admin/orgs/{org.id}/", {"name": "Renamed"}, format="json")
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.name == "Renamed"


def test_disable_org_stops_scheduling(staff_api, org, monitor, fake_redis):
    response = staff_api.post(f"/api/v1/admin/orgs/{org.id}/disable/")
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.is_active is False
    assert AuditEvent.objects.filter(event_type="admin.org_disabled", severity="high").exists()

    assert schedule_due_monitors() == 0

    # re-enable: monitors are scheduled again
    assert staff_api.post(f"/api/v1/admin/orgs/{org.id}/enable/").status_code == 200
    org.refresh_from_db()
    assert org.is_active is True
    assert schedule_due_monitors() > 0


def test_disable_is_idempotent(staff_api, org):
    staff_api.post(f"/api/v1/admin/orgs/{org.id}/disable/")
    staff_api.post(f"/api/v1/admin/orgs/{org.id}/disable/")
    assert AuditEvent.objects.filter(event_type="admin.org_disabled").count() == 1


def test_delete_org_cascades(staff_api, org, monitor):
    response = staff_api.delete(f"/api/v1/admin/orgs/{org.id}/")
    assert response.status_code == 204
    assert not Organization.objects.filter(pk=org.id).exists()
    assert not Monitor.objects.filter(pk=monitor.id).exists()
    assert AuditEvent.objects.filter(event_type="admin.org_deleted", severity="high").exists()


def test_disabled_org_visible_in_me_payload(api, org, staff_api):
    staff_api.post(f"/api/v1/admin/orgs/{org.id}/disable/")
    response = api.get("/api/v1/me")
    assert response.data["organizations"][0]["is_active"] is False


# --- users -----------------------------------------------------------------


def test_user_list_and_search(staff_api, user, other_user):
    response = staff_api.get("/api/v1/admin/users/?q=alice")
    usernames = [u["username"] for u in response.data["results"]]
    assert usernames == ["alice"]

    orgs = response.data["results"][0]["organizations"]
    assert orgs[0]["role"] == "owner"


def test_user_filter_is_active(staff_api, user, other_user):
    other_user.is_active = False
    other_user.save(update_fields=["is_active"])
    response = staff_api.get("/api/v1/admin/users/?is_active=false")
    usernames = [u["username"] for u in response.data["results"]]
    assert usernames == ["bob"]


def test_admin_creates_user(staff_api):
    response = staff_api.post(
        "/api/v1/admin/users/",
        {"username": "carol", "email": "carol@example.com", "password": "s3cure-Pass-99"},
        format="json",
    )
    assert response.status_code == 201, response.data
    carol = get_user_model().objects.get(username="carol")
    assert carol.check_password("s3cure-Pass-99")
    # the post_save signal provisions a personal org, like self-signup
    assert carol.memberships.exists()
    assert AuditEvent.objects.filter(event_type="admin.user_created").exists()


def test_weak_password_rejected(staff_api):
    response = staff_api.post(
        "/api/v1/admin/users/",
        {"username": "dave", "email": "dave@example.com", "password": "123"},
        format="json",
    )
    assert response.status_code == 400
    assert not get_user_model().objects.filter(username="dave").exists()


def test_staff_deactivates_regular_user(staff_api, user):
    response = staff_api.patch(f"/api/v1/admin/users/{user.id}/", {"is_active": False}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active is False
    assert AuditEvent.objects.filter(event_type="admin.user_updated", severity="high").exists()


def test_staff_cannot_grant_staff(staff_api, user):
    response = staff_api.patch(f"/api/v1/admin/users/{user.id}/", {"is_staff": True}, format="json")
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.is_staff is False


def test_superuser_grants_staff(super_api, user):
    response = super_api.patch(f"/api/v1/admin/users/{user.id}/", {"is_staff": True}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_staff is True


def test_staff_cannot_manage_privileged_accounts(staff_api, superuser, staff_user):
    other_staff = get_user_model().objects.create_user(
        "staffer2", "staffer2@example.com", "pw", is_staff=True
    )
    for target in (superuser, other_staff):
        assert (
            staff_api.patch(
                f"/api/v1/admin/users/{target.id}/", {"is_active": False}, format="json"
            ).status_code
            == 403
        )
        assert staff_api.delete(f"/api/v1/admin/users/{target.id}/").status_code == 403


def test_admin_cannot_modify_own_account(staff_api, staff_user):
    response = staff_api.patch(
        f"/api/v1/admin/users/{staff_user.id}/", {"is_active": False}, format="json"
    )
    assert response.status_code == 403
    assert staff_api.delete(f"/api/v1/admin/users/{staff_user.id}/").status_code == 403


def test_delete_user(staff_api, user):
    assert staff_api.delete(f"/api/v1/admin/users/{user.id}/").status_code == 204
    assert not get_user_model().objects.filter(pk=user.id).exists()
    assert AuditEvent.objects.filter(event_type="admin.user_deleted", severity="high").exists()


def test_set_password(staff_api, user):
    response = staff_api.post(
        f"/api/v1/admin/users/{user.id}/set-password/", {"password": "n3w-Secret-77"}, format="json"
    )
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.check_password("n3w-Secret-77")
    assert AuditEvent.objects.filter(event_type="admin.user_password_set", severity="high").exists()


def test_set_password_rejects_weak(staff_api, user):
    response = staff_api.post(
        f"/api/v1/admin/users/{user.id}/set-password/", {"password": "pw"}, format="json"
    )
    assert response.status_code == 400


def test_set_password_rejects_username_similarity(staff_api, user):
    response = staff_api.post(
        f"/api/v1/admin/users/{user.id}/set-password/", {"password": "alice"}, format="json"
    )
    assert response.status_code == 400


def test_me_exposes_staff_flag(staff_api, api):
    assert staff_api.get("/api/v1/me").data["user"]["is_staff"] is True
    assert api.get("/api/v1/me").data["user"]["is_staff"] is False


# --- platform stats -------------------------------------------------------


def test_platform_stats(staff_api, user, org, monitor, worker_and_token, regions):
    worker, _ = worker_and_token
    worker.last_seen_at = timezone.now()
    worker.save(update_fields=["last_seen_at"])
    CheckResult.objects.create(monitor=monitor, region_code="eu-west", checked_at=timezone.now(), ok=True)
    CheckResult.objects.create(monitor=monitor, region_code="eu-west", checked_at=timezone.now(), ok=False)
    AlertEvent.objects.create(monitor=monitor, event_type="down", summary="down")

    stats = staff_api.get("/api/v1/admin/stats").data
    assert stats["users"]["total"] == 2  # alice + staffer
    assert stats["organizations"] == {"total": 2, "active": 2, "disabled": 0}
    assert stats["monitors"]["total"] == 1
    assert stats["monitors"]["unknown"] == 1
    assert stats["workers"] == {"total": 1, "active": 1, "online": 1}
    assert stats["regions"] == {"total": 2, "active": 2}
    assert stats["checks_24h"] == {"total": 2, "failed": 1}
    assert stats["alerts"]["open"] == 1
    assert stats["audit_24h"]["total"] == AuditEvent.objects.count()


# --- audit insights --------------------------------------------------------


@pytest.fixture
def audit_events(db, org):
    from apps.audit.services import record

    record("monitor.created", "Monitor 'a' created", organization=org, actor="alice")
    record("monitor.deleted", "Monitor 'a' deleted", severity="medium", organization=org, actor="alice")
    record("worker.auth_failed", "Bad worker token", severity="high")  # platform-level, no org
    return AuditEvent.objects.all()


def test_admin_audit_includes_platform_events(staff_api, audit_events):
    response = staff_api.get("/api/v1/admin/audit/")
    types = [e["event_type"] for e in response.data["results"]]
    assert "worker.auth_failed" in types  # invisible in the org-scoped endpoint
    assert "monitor.created" in types


def test_admin_audit_filters(staff_api, audit_events, org):
    assert [
        e["event_type"]
        for e in staff_api.get("/api/v1/admin/audit/?severity=high").data["results"]
    ] == ["worker.auth_failed"]

    assert [
        e["event_type"]
        for e in staff_api.get("/api/v1/admin/audit/?event_type=monitor.created").data["results"]
    ] == ["monitor.created"]

    by_org = staff_api.get(f"/api/v1/admin/audit/?organization={org.id}").data["results"]
    assert {e["event_type"] for e in by_org} == {"monitor.created", "monitor.deleted"}

    by_actor = staff_api.get("/api/v1/admin/audit/?actor=alice").data["results"]
    assert len(by_actor) == 2

    by_q = staff_api.get("/api/v1/admin/audit/?q=bad worker").data["results"]
    assert [e["event_type"] for e in by_q] == ["worker.auth_failed"]


def test_admin_audit_bogus_organization_filter(staff_api, audit_events):
    response = staff_api.get("/api/v1/admin/audit/?organization=not-a-uuid")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_audit_summary(staff_api, audit_events):
    response = staff_api.get("/api/v1/admin/audit/summary/?days=7")
    assert response.status_code == 200
    data = response.data
    assert data["days"] == 7
    assert data["total"] == 3
    assert data["by_severity"] == {"info": 1, "medium": 1, "high": 1}
    assert data["by_event_type"]["worker.auth_failed"] == 1
    assert sum(day["count"] for day in data["by_day"]) == 3


def test_audit_summary_clamps_days(staff_api, audit_events):
    assert staff_api.get("/api/v1/admin/audit/summary/?days=9999").data["days"] == 90
    assert staff_api.get("/api/v1/admin/audit/summary/?days=bogus").data["days"] == 7


def test_org_scoped_audit_still_hides_platform_events(api, audit_events, org):
    response = api.get("/api/v1/audit/")
    types = [e["event_type"] for e in response.data["results"]]
    assert "worker.auth_failed" not in types


# --- schema ---------------------------------------------------------------


def test_admin_endpoints_in_schema(staff_api):
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    assert "/api/v1/admin/workers/" in paths
    assert "/api/v1/admin/orgs/{id}/disable/" in paths
    assert "/api/v1/admin/users/{id}/set-password/" in paths
    assert "/api/v1/admin/stats" in paths
    assert "/api/v1/admin/audit/summary/" in paths
