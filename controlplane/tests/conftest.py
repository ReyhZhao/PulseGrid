import fakeredis
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.monitors.models import Monitor, Region
from apps.workerapi.models import Worker
from pulsegrid import queues


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """All queue operations go through an in-memory Redis."""
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(queues, "get_redis", lambda: client)
    return client


@pytest.fixture
def regions(db):
    return [
        Region.objects.create(code="eu-west", name="Europe West"),
        Region.objects.create(code="us-east", name="US East"),
    ]


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", "alice@example.com", "pw")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", "bob@example.com", "pw")


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user("staffer", "staffer@example.com", "pw", is_staff=True)


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser("root", "root@example.com", "pw")


@pytest.fixture
def staff_api(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def super_api(superuser):
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def org(user):
    # Created automatically by the accounts signal on first login/creation.
    return user.memberships.get().organization


@pytest.fixture
def other_org(other_user):
    return other_user.memberships.get().organization


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_api(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.fixture
def monitor(org, regions):
    return Monitor.objects.create(
        organization=org,
        name="Example",
        url="https://example.com/health",
        interval_seconds=60,
    )


@pytest.fixture
def worker_and_token(regions):
    worker, token = Worker.issue("test-worker", regions[0])
    return worker, token


@pytest.fixture
def worker_api(worker_and_token):
    _worker, token = worker_and_token
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
