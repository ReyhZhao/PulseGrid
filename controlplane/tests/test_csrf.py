"""CSRF posture of the API surface.

Session-authenticated browser endpoints must enforce CSRF (DRF's
SessionAuthentication does this on unsafe methods); the token-authenticated
worker API must not require it; and the token bootstrap endpoint must hand
out a usable token both as a cookie and in the body.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_csrf_endpoint_returns_token_and_sets_cookie(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrftoken"]
    assert len(token) == 64  # masked CSRF token
    assert "csrftoken" in response.cookies


def test_session_api_rejects_unsafe_request_without_csrf(user, org, regions):
    client = Client(enforce_csrf_checks=True)
    client.login(username="alice", password="pw")
    response = client.post(
        "/api/v1/monitors/",
        {"organization": str(org.id), "name": "X", "url": "https://example.com"},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_session_api_accepts_request_with_csrf_token(user, org, regions):
    client = Client(enforce_csrf_checks=True)
    client.login(username="alice", password="pw")
    token = client.get("/api/v1/auth/csrf").json()["csrftoken"]
    response = client.post(
        "/api/v1/monitors/",
        {"organization": str(org.id), "name": "X", "url": "https://example.com"},
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 201, response.json()


def test_worker_api_requires_no_csrf(worker_and_token, regions):
    """Machine clients authenticate with bearer tokens, never sessions, so
    DRF applies no CSRF check — this must keep working without cookies."""
    worker, token = worker_and_token
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        "/api/v1/worker/heartbeat",
        {},
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
