"""Org self-service: rename, members, invitations, onboarding."""

import pytest
from django.core import mail

from apps.accounts.models import Membership, OrganizationInvitation
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


# --- rename ------------------------------------------------------------------


def test_owner_can_rename_org(api, org):
    response = api.patch(f"/api/v1/orgs/{org.id}/", {"name": "Acme Corp"}, format="json")
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.name == "Acme Corp"
    assert AuditEvent.objects.filter(event_type="org.renamed").exists()


def test_member_cannot_rename_org(api, other_user, org):
    Membership.objects.create(organization=org, user=other_user, role=Membership.Role.MEMBER)
    from rest_framework.test import APIClient

    member_client = APIClient()
    member_client.force_authenticate(user=other_user)
    response = member_client.patch(f"/api/v1/orgs/{org.id}/", {"name": "Hijacked"}, format="json")
    assert response.status_code == 403


def test_outsider_cannot_see_org(other_api, org):
    assert other_api.get(f"/api/v1/orgs/{org.id}/").status_code == 404


# --- members -----------------------------------------------------------------


def test_members_list(api, user, other_user, org):
    Membership.objects.create(organization=org, user=other_user, role=Membership.Role.MEMBER)
    response = api.get(f"/api/v1/orgs/{org.id}/members/")
    assert response.status_code == 200
    roles = {m["username"]: m["role"] for m in response.data}
    assert roles == {"alice": "owner", "bob": "member"}


def test_owner_can_remove_member(api, other_user, org):
    Membership.objects.create(organization=org, user=other_user, role=Membership.Role.MEMBER)
    response = api.delete(f"/api/v1/orgs/{org.id}/members/{other_user.id}/")
    assert response.status_code == 204
    assert not Membership.objects.filter(organization=org, user=other_user).exists()
    assert AuditEvent.objects.filter(event_type="org.member_removed").exists()


def test_cannot_remove_last_owner(api, user, org):
    response = api.delete(f"/api/v1/orgs/{org.id}/members/{user.id}/")
    assert response.status_code == 400
    assert Membership.objects.filter(organization=org, user=user).exists()


# --- invitations -------------------------------------------------------------


def test_owner_invites_and_email_is_sent(api, org):
    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/",
        {"email": "newcolleague@example.com", "role": "member"},
        format="json",
    )
    assert response.status_code == 201, response.data
    invitation = OrganizationInvitation.objects.get()
    assert len(mail.outbox) == 1
    assert "newcolleague@example.com" in mail.outbox[0].to
    assert invitation.token in mail.outbox[0].body
    assert AuditEvent.objects.filter(event_type="org.member_invited", severity="medium").exists()


def test_member_cannot_invite(api, other_user, org):
    Membership.objects.create(organization=org, user=other_user, role=Membership.Role.MEMBER)
    from rest_framework.test import APIClient

    member_client = APIClient()
    member_client.force_authenticate(user=other_user)
    response = member_client.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "x@example.com"}, format="json"
    )
    assert response.status_code == 403


def test_cannot_invite_existing_member(api, other_user, org):
    Membership.objects.create(organization=org, user=other_user, role=Membership.Role.MEMBER)
    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": other_user.email}, format="json"
    )
    assert response.status_code == 400


def test_accept_invitation(api, other_api, other_user, org):
    api.post(f"/api/v1/orgs/{org.id}/invite/", {"email": other_user.email}, format="json")
    token = OrganizationInvitation.objects.get().token

    response = other_api.post("/api/v1/invitations/accept", {"token": token}, format="json")
    assert response.status_code == 200
    assert response.data["joined"] is True
    assert Membership.objects.filter(organization=org, user=other_user, role="member").exists()

    # token is single-use
    response = other_api.post("/api/v1/invitations/accept", {"token": token}, format="json")
    assert response.status_code == 400


def test_accept_expired_invitation(other_api, org, user):
    from datetime import timedelta

    from django.utils import timezone

    invitation = OrganizationInvitation.objects.create(
        organization=org,
        email="late@example.com",
        invited_by=user,
        expires_at=timezone.now() - timedelta(days=1),
    )
    response = other_api.post("/api/v1/invitations/accept", {"token": invitation.token}, format="json")
    assert response.status_code == 400


def test_revoke_invitation(api, org):
    api.post(f"/api/v1/orgs/{org.id}/invite/", {"email": "gone@example.com"}, format="json")
    invitation = OrganizationInvitation.objects.get()

    response = api.delete(f"/api/v1/orgs/{org.id}/invitations/{invitation.id}/")
    assert response.status_code == 204
    assert not OrganizationInvitation.objects.exists()

    listing = api.get(f"/api/v1/orgs/{org.id}/invitations/")
    assert listing.data == []


# --- onboarding --------------------------------------------------------------


def test_new_user_needs_onboarding(api):
    response = api.get("/api/v1/me")
    assert response.data["onboarding_complete"] is False


def test_onboarding_complete_flow(api, user):
    response = api.post("/api/v1/onboarding/complete")
    assert response.status_code == 200
    assert response.data["onboarding_complete"] is True
    # idempotent
    assert api.post("/api/v1/onboarding/complete").data["onboarding_complete"] is True
    assert AuditEvent.objects.filter(event_type="user.onboarded").count() == 1


def test_me_patch_updates_names(api, user):
    response = api.patch("/api/v1/me", {"first_name": "Alice", "last_name": "Ng"}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Alice"
    assert user.last_name == "Ng"
