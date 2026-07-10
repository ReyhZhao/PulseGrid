"""Multi-tenancy isolation: users must never see or touch another org's data."""

import pytest

pytestmark = pytest.mark.django_db


def test_monitor_list_only_shows_own_org(api, other_api, monitor):
    response = api.get("/api/v1/monitors/")
    assert response.status_code == 200
    assert {m["id"] for m in response.data["results"]} == {str(monitor.id)}

    response = other_api.get("/api/v1/monitors/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_monitor_detail_hidden_from_other_org(other_api, monitor):
    assert other_api.get(f"/api/v1/monitors/{monitor.id}/").status_code == 404
    assert other_api.delete(f"/api/v1/monitors/{monitor.id}/").status_code == 404
    assert other_api.post(f"/api/v1/monitors/{monitor.id}/pause/").status_code == 404


def test_cannot_create_monitor_in_foreign_org(other_api, org, regions):
    response = other_api.post(
        "/api/v1/monitors/",
        {"organization": str(org.id), "name": "Sneaky", "url": "https://example.com"},
        format="json",
    )
    assert response.status_code == 400
    assert "organization" in response.data


def test_alerts_and_channels_are_scoped(api, other_api, org, monitor):
    response = api.post(
        "/api/v1/channels/",
        {
            "organization": str(org.id),
            "name": "Ops mail",
            "channel_type": "email",
            "config": {"to": ["ops@example.com"]},
        },
        format="json",
    )
    assert response.status_code == 201
    channel_id = response.data["id"]

    assert other_api.get(f"/api/v1/channels/{channel_id}/").status_code == 404
    assert other_api.get("/api/v1/channels/").data["results"] == []


def test_api_requires_authentication(db):
    from rest_framework.test import APIClient

    anonymous = APIClient()
    assert anonymous.get("/api/v1/monitors/").status_code == 403
