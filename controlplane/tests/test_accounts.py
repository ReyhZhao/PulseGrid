import pytest

pytestmark = pytest.mark.django_db


def test_new_user_gets_personal_org(user):
    membership = user.memberships.get()
    assert membership.role == "owner"
    assert membership.organization.slug == "alice"


def test_me_endpoint(api, user, org):
    response = api.get("/api/v1/me")
    assert response.status_code == 200
    assert response.data["user"]["username"] == "alice"
    orgs = response.data["organizations"]
    assert len(orgs) == 1
    assert orgs[0]["role"] == "owner"


def test_healthz(client):
    assert client.get("/healthz").status_code == 200
