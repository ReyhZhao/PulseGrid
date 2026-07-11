"""On-demand Authentik provisioning during org invitations."""

import pytest
import responses as responses_lib
from django.core import mail

from apps.accounts.models import OrganizationInvitation

pytestmark = pytest.mark.django_db

AUTHENTIK = "https://auth.vels.online"

AUTHENTIK_SETTINGS = {
    "PUBLIC_URL": AUTHENTIK,
    "TOKEN": "ak-service-token",
    "ENROLLMENT_FLOW": "pulsegrid-enrollment",
}

FLOW_PK = "11111111-2222-3333-4444-555555555555"
ITOKEN = "99999999-8888-7777-6666-555555555555"


@pytest.fixture
def authentik_enabled(settings):
    settings.PULSEGRID_AUTHENTIK = AUTHENTIK_SETTINGS
    settings.PULSEGRID_FRONTEND_URL = "https://pulsegrid.vels.online"
    return settings


def mock_user_lookup(found: bool):
    responses_lib.add(
        responses_lib.GET,
        f"{AUTHENTIK}/api/v3/core/users/",
        json={"results": [{"pk": 7}] if found else []},
    )


def mock_flow_lookup(found: bool = True):
    responses_lib.add(
        responses_lib.GET,
        f"{AUTHENTIK}/api/v3/flows/instances/",
        json={"results": [{"pk": FLOW_PK}] if found else []},
    )


def mock_invitation_create():
    responses_lib.add(
        responses_lib.POST,
        f"{AUTHENTIK}/api/v3/stages/invitation/invitations/",
        json={"pk": ITOKEN},
        status=201,
    )


@responses_lib.activate
def test_unknown_user_gets_enrollment_link(authentik_enabled, api, org):
    mock_user_lookup(found=False)
    mock_flow_lookup()
    mock_invitation_create()

    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "new@example.com"}, format="json"
    )
    assert response.status_code == 201

    body = mail.outbox[0].body
    assert f"{AUTHENTIK}/if/flow/pulsegrid-enrollment/?itoken={ITOKEN}" in body
    assert "next=" in body

    # the Authentik invitation was created with the right shape
    create_call = responses_lib.calls[-1].request
    assert "ak-service-token" in create_call.headers["Authorization"]
    assert b'"single_use": true' in create_call.body or b'"single_use":true' in create_call.body
    assert b"new@example.com" in create_call.body

    invitation = OrganizationInvitation.objects.get()
    assert f"/invite/{invitation.token}" in body


@responses_lib.activate
def test_existing_idp_user_gets_plain_invite(authentik_enabled, api, org):
    mock_user_lookup(found=True)

    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "known@example.com"}, format="json"
    )
    assert response.status_code == 201
    body = mail.outbox[0].body
    assert "/if/flow/" not in body
    assert "Accept the invitation:" in body
    # only the user lookup hit Authentik
    assert len(responses_lib.calls) == 1


@responses_lib.activate
def test_authentik_outage_falls_back_to_plain_invite(authentik_enabled, api, org):
    responses_lib.add(responses_lib.GET, f"{AUTHENTIK}/api/v3/core/users/", status=503)

    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "new@example.com"}, format="json"
    )
    assert response.status_code == 201  # invite still created
    assert len(mail.outbox) == 1
    assert "/if/flow/" not in mail.outbox[0].body


@responses_lib.activate
def test_missing_enrollment_flow_falls_back(authentik_enabled, api, org):
    mock_user_lookup(found=False)
    mock_flow_lookup(found=False)

    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "new@example.com"}, format="json"
    )
    assert response.status_code == 201
    assert "/if/flow/" not in mail.outbox[0].body


def test_provisioning_disabled_makes_no_api_calls(api, org):
    # No PULSEGRID_AUTHENTIK override: TOKEN/FLOW are empty in test settings,
    # and no `responses` mock is active — a real HTTP call would error out.
    response = api.post(
        f"/api/v1/orgs/{org.id}/invite/", {"email": "new@example.com"}, format="json"
    )
    assert response.status_code == 201
    assert "Accept the invitation:" in mail.outbox[0].body
