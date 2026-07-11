import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db


def test_disabled_by_default(client):
    assert client.get("/api/v1/me").status_code == 403


def test_auto_login_requires_debug(settings):
    settings.DEV_AUTO_LOGIN = True
    settings.DEBUG = False
    assert Client().get("/api/v1/me").status_code == 403


def test_auto_login_as_superuser(settings):
    settings.DEV_AUTO_LOGIN = True
    settings.DEBUG = True
    get_user_model().objects.create_superuser("admin", "admin@localhost", "admin")

    response = Client().get("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
