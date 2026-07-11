"""Self-service registration: auth config discovery and local signup."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db


# --- auth config discovery ----------------------------------------------------


def test_auth_config_is_public(client):
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert data["signup_enabled"] is True
    assert data["authentik_enabled"] is False  # no OIDC configured in tests
    assert data["authentik_signup_url"] is None


def test_auth_config_reports_authentik_signup_flow(client, settings):
    settings.PULSEGRID_AUTHENTIK = {
        "PUBLIC_URL": "https://auth.vels.online",
        "TOKEN": "x",
        "ENROLLMENT_FLOW": "pulsegrid-enrollment",
        "SIGNUP_FLOW": "pulsegrid-signup",
    }
    data = client.get("/api/v1/auth/config").json()
    assert data["authentik_signup_url"] == "https://auth.vels.online/if/flow/pulsegrid-signup/"


def test_auth_config_reflects_disabled_signup(client, settings):
    settings.PULSEGRID_ALLOW_SIGNUP = False
    assert client.get("/api/v1/auth/config").json()["signup_enabled"] is False


# --- local signup via allauth headless -----------------------------------------


def signup(client, **overrides):
    payload = {"username": "newbie", "email": "newbie@example.com", "password": "s3cure-pass-123"}
    payload.update(overrides)
    return client.post(
        "/_allauth/browser/v1/auth/signup", payload, content_type="application/json"
    )


def test_signup_creates_user_with_org_and_session(client):
    response = signup(client)
    assert response.status_code == 200, response.content
    assert response.json()["meta"]["is_authenticated"] is True

    user = get_user_model().objects.get(username="newbie")
    membership = user.memberships.get()
    assert membership.role == "owner"

    # fresh users are funneled into onboarding
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["onboarding_complete"] is False


def test_signup_rejected_when_disabled(settings):
    settings.PULSEGRID_ALLOW_SIGNUP = False
    response = signup(Client())
    assert response.status_code == 403
    assert not get_user_model().objects.filter(username="newbie").exists()


def test_signup_validates_password(client):
    response = signup(client, password="123")
    assert response.status_code == 400
